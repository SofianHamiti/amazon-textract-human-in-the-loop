import re
import json
import boto3

iam = boto3.client('iam')
s3 = boto3.client('s3')
sagemaker = boto3.client('sagemaker')

task_template = r"""
<script src="https://assets.crowd.aws/crowd-html-elements.js"></script>
{% capture s3_arn %}http://s3.amazonaws.com/{{ task.input.aiServiceRequest.document.s3Object.bucket }}/{{ task.input.aiServiceRequest.document.s3Object.name }}{% endcapture %}
<crowd-form>
  <crowd-textract-analyze-document 
      src="{{ s3_arn | grant_read_access }}" 
      initial-value="{{ task.input.selectedAiServiceResponse.blocks }}" 
      header="Review the key-value pairs listed on the right and correct them if they don't match the following document." 
      no-key-edit="" 
      no-geometry-edit="" 
      keys="{{ task.input.humanLoopContext.importantFormKeys }}" 
      block-types="['KEY_VALUE_SET']">
    <short-instructions header="Instructions">
        <p>Click on a key-value block to highlight the corresponding key-value pair in the document.
        </p><p><br></p>
        <p>If it is a valid key-value pair, review the content for the value. If the content is incorrect, correct it.
        </p><p><br></p>
        <p>The text of the value is incorrect, correct it.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/correct-value-text.png">
        </p><p><br></p>
        <p>A wrong value is identified, correct it.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/correct-value.png">
        </p><p><br></p>
        <p>If it is not a valid key-value relationship, choose No.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/not-a-key-value-pair.png">
        </p><p><br></p>
        <p>If you can’t find the key in the document, choose Key not found.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/key-is-not-found.png">
        </p><p><br></p>
        <p>If the content of a field is empty, choose Value is blank.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/value-is-blank.png">
        </p><p><br></p>
        <p><strong>Examples</strong></p>
        <p>Key and value are often displayed next or below to each other.
        </p><p><br></p>
        <p>Key and value displayed in one line.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/sample-key-value-pair-1.png">
        </p><p><br></p>
        <p>Key and value displayed in two lines.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/sample-key-value-pair-2.png">
        </p><p><br></p>
        <p>If the content of the value has multiple lines, enter all the text without line break. 
        Include all value text even if it extends beyond the highlight box.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/multiple-lines.png"></p>
    </short-instructions>
    <full-instructions header="Instructions"></full-instructions>
  </crowd-textract-analyze-document>
</crowd-form>
"""

def create_task_ui(task_ui_name):
    '''
    Creates a Human Task UI resource.

    Returns:
    struct: HumanTaskUiArn
    '''
    response = sagemaker.create_human_task_ui(
        HumanTaskUiName=task_ui_name,
        UiTemplate={'Content': task_template})
    return response


def create_flow_definition(flow_definition_name, workteam_arn, human_task_ui_arn, role_arn, a2i_output_path):
    '''
    Creates a Flow Definition resource

    Returns:
    struct: FlowDefinitionArn
    '''
    # Visit https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-human-fallback-conditions-json-schema.html for more information on this schema.
    humanLoopActivationConditions = json.dumps(
        {
            "Conditions": [
                {
                  "Or": [
                    
                    {
                        "ConditionType": "ImportantFormKeyConfidenceCheck",
                        "ConditionParameters": {
                            "ImportantFormKey": "Mail address",
                            "ImportantFormKeyAliases": ["Mail Address:","Mail address:", "Mailing Add:","Mailing Addresses"],
                            "KeyValueBlockConfidenceLessThan": 100,
                            "WordBlockConfidenceLessThan": 100
                        }
                    },
                    {
                        "ConditionType": "MissingImportantFormKey",
                        "ConditionParameters": {
                            "ImportantFormKey": "Mail address",
                            "ImportantFormKeyAliases": ["Mail Address:","Mail address:","Mailing Add:","Mailing Addresses"]
                        }
                    },
                    {
                        "ConditionType": "ImportantFormKeyConfidenceCheck",
                        "ConditionParameters": {
                            "ImportantFormKey": "Phone Number",
                            "ImportantFormKeyAliases": ["Phone number:", "Phone No.:", "Number:"],
                            "KeyValueBlockConfidenceLessThan": 100,
                            "WordBlockConfidenceLessThan": 100
                        }
                    },
                    {
                      "ConditionType": "ImportantFormKeyConfidenceCheck",
                      "ConditionParameters": {
                        "ImportantFormKey": "*",
                        "KeyValueBlockConfidenceLessThan": 100,
                        "WordBlockConfidenceLessThan": 100
                      }
                    },
                    {
                      "ConditionType": "ImportantFormKeyConfidenceCheck",
                      "ConditionParameters": {
                        "ImportantFormKey": "*",
                        "KeyValueBlockConfidenceGreaterThan": 0,
                        "WordBlockConfidenceGreaterThan": 0
                      }
                    }
            ]
        }
            ]
        }
    )

    response = sagemaker.create_flow_definition(
            FlowDefinitionName= flow_definition_name,
            RoleArn= role_arn,
            HumanLoopConfig= {
                "WorkteamArn": workteam_arn,
                "HumanTaskUiArn": human_task_ui_arn,
                "TaskCount": 1,
                "TaskDescription": "Document analysis sample task description",
                "TaskTitle": "Document analysis sample task"
            },
            HumanLoopRequestSource={
                "AwsManagedHumanLoopRequestSource": "AWS/Textract/AnalyzeDocument/Forms/V1"
            },
            HumanLoopActivationConfig={
                "HumanLoopActivationConditionsConfig": {
                    "HumanLoopActivationConditions": humanLoopActivationConditions
                }
            },
            OutputConfig={
                "S3OutputPath" : a2i_output_path
            }
        )
    
    return response['FlowDefinitionArn']

def describe_flow_definition(name):
    '''
    Describes Flow Definition

    Returns:
    struct: response from DescribeFlowDefinition API invocation
    '''
    return sagemaker.describe_flow_definition(FlowDefinitionName=name)

def retrieve_a2i_results_from_output_s3_uri(bucket, a2i_s3_output_uri):
    '''
    Gets the json file published by A2I and returns a deserialized object
    '''
    splitted_string = re.split('s3://' +  bucket + '/', a2i_s3_output_uri)
    output_bucket_key = splitted_string[1]

    response = s3.get_object(Bucket=bucket, Key=output_bucket_key)
    content = response["Body"].read()
    return json.loads(content)

def add_cors_policy(bucket_name):
    try:
        # Define the configuration rules
        cors_configuration = {
            'CORSRules': [{
                "AllowedHeaders": [],
                "AllowedMethods": [
                    "GET"
                ],
                "AllowedOrigins": [
                    "*"
                ],
                "ExposeHeaders": []
            }]
        }

        # Set the CORS configuration
        s3.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_configuration)
        print(f'CORS rules added to {bucket_name}')
              
    except Exception as e:
        print(e)

def update_notebook_role(role_name):
    try:
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonTextractFullAccess'
        )
        
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonSageMakerFullAccess'
        )  
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess'
        )  
    except Exception as e:
        print(e)

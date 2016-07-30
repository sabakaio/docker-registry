import os
from troposphere import GetAtt, Join, Ref
from troposphere import awslambda, cloudformation as cf
from helpers.iam import make_role, describe_images, logs_writer


def ami_lookup(template):
    name = 'AMILookupFunction'
    role = make_role(name, template, describe_images, logs_writer)

    with open(os.path.join(os.path.dirname(__file__), 'funcrion.js')) as f:
        func = awslambda.Function(
            name, template,
            Code=awslambda.Code(
                ZipFile=Join('', list(f.readlines()))
            ),
            Handler='index.handler',
            Role=GetAtt(role, 'Arn'),
            Runtime='nodejs',
            Timeout=30
        )

    return cf.CustomResource(
        'AMI', template,
        ServiceToken=GetAtt(func, 'Arn'),
        Region=Ref('AWS::Region'),
        Architecture='HVM64'
    )

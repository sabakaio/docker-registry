from awacs.aws import Allow, Statement, Principal, Policy, Action, BaseARN
from awacs.ec2 import DescribeImages
from awacs.logs import CreateLogGroup, CreateLogStream, PutLogEvents
from awacs.sts import AssumeRole

from troposphere import Ref, Join
from troposphere import iam


def bucket_full_access(bucket, name=None, template=None):
    name = (name or '').title() + bucket.title + 'S3BucketFullAccess'
    return iam.Policy(
        PolicyName=name,
        PolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[
                        Action('s3', '*'),
                    ],
                    Resource=[
                        Join('', ['arn:aws:s3:::', Ref(bucket)]),
                        Join('', ['arn:aws:s3:::', Ref(bucket), '/*']),
                    ],
                ),
            ]
        )
    )


def describe_images(name=None, template=None):
    name = (name or '').title() + 'ImageReader'
    return iam.Policy(
        PolicyName=name,
        PolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[DescribeImages],
                    Resource=['*'],
                ),
            ]
        )
    )


def logs_writer(name=None, template=None):
    name = (name or '').title() + 'LogsWriter'
    return iam.Policy(
        PolicyName=name,
        PolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[
                        CreateLogGroup,
                        CreateLogStream,
                        PutLogEvents,
                    ],
                    Resource=[BaseARN('logs', '*', '*', '*')],
                ),
            ]
        )
    )


def make_role(name, template, assume_to, *policies):
    def _policy(p):
        if callable(p):
            return p(name=name, template=template)
        return p

    if not isinstance(assume_to, list):
        assume_to = [assume_to]

    return iam.Role(
        name + 'Role', template, Path='/',
        AssumeRolePolicyDocument=Policy(Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal('Service', assume_to)
            )
        ]),
        Policies=[_policy(p) for p in policies]
    )


def make_instance_profile(name, template, *policies):
    role = make_role(name, template, 'ec2.amazonaws.com', *policies)
    return iam.InstanceProfile(name, template, Roles=[Ref(role)])

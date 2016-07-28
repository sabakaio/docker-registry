from awacs.aws import Allow, Statement, Principal, Policy, Action
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


def make_instance_profile(name, template, *policies):
    def _policy(p):
        if callable(p):
            return p(name=name, template=template)
        return p

    role = iam.Role(
        name + 'Role', template, Path='/',
        AssumeRolePolicyDocument=Policy(Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal('Service', ['ec2.amazonaws.com'])
            )
        ]),
        Policies=[_policy(p) for p in policies]
    )
    return iam.InstanceProfile(name, template, Roles=[Ref(role)])

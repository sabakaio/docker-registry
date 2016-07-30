from troposphere import Ref, Base64, Join
from troposphere import cloudformation as cf, ec2, autoscaling as au


def certbot(domain, email):
    script_name = '/opt/certbot-auto'
    conf_dir = '/opt/certs'
    return cf.InitConfig(
        'certbot',
        files={
            script_name: {
                'source': 'https://dl.eff.org/certbot-auto',
                'mode': '000755',
                'owner': 'root',
                'group': 'root',
            },
        },
        commands={
            'get_cert': {
                'command': Join(' ', [
                    script_name, 'certonly',
                    '--config-dir', conf_dir,
                    '--standalone --debug --agree-tos --non-interactive',
                    '-d', domain,
                    '--email', email,
                ])
            }
        }
    )


def add_init(target, *configs):
    assert isinstance(target, (ec2.Instance, au.LaunchConfiguration))
    params = Join('', [
        'export CFN_PARAMS=\'',
        ' --region ', Ref('AWS::Region'),
        ' --stack ', Ref('AWS::StackName'),
        ' --resource ' + target.title + '\'',
    ])
    target.UserData = Base64(Join('\n', [
        '#!/bin/bash -xe',
        'yum update -y',
        params,
        '/opt/aws/bin/cfn-init -v -c default $CFN_PARAMS',
        '/opt/aws/bin/cfn-signal -e 0 $CFN_PARAMS'
    ]))

    configs = [callable(c) and c() or c for c in configs]
    target.Metadata = cf.Init(
        cf.InitConfigSets(default=[c.title for c in configs]),
        **{c.title: c for c in configs})
    return target

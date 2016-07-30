from troposphere import Ref, Base64, Join
from troposphere import cloudformation as cf, ec2, autoscaling as au


def docker():
    return cf.InitConfig(
        'Docker',
        packages={'yum': {'docker': []}},
        commands={
            'docker_user': {
                'command': 'usermod -aG docker ec2-user'
            },
            'install_compose': {
                'command': 'pip install docker-compose'
            },
        },
        services={
            'sysvinit': {
                'docker': {
                    'enabled': True,
                    'ensureRunning': True
                }
            }
        }
    )


def docker_compose(name, compose_yml):
    name = name.lower()
    compose_file = '/opt/{n}/docker-compose.yml'.format(n=name)
    return cf.InitConfig(
        'Compose' + name.title(),
        files={
            compose_file: {
                'content': compose_yml,
                'mode': '000664',
                'owner': 'root',
                'group': 'docker',
            },
        },
        commands={
            'up': {
                'command': '/usr/local/bin/docker-compose -f {f} up -d'.format(f=compose_file)
            },
        }
    )


def certbot(domain, email, conf_dir='/opt/certs/', copy_to=None):
    script_name = '/opt/certbot-auto'
    commands = {
        '1_get_cert': {
            'command': Join(' ', [
                script_name, 'certonly',
                '--config-dir', conf_dir,
                '--standalone --debug --agree-tos --non-interactive',
                '-d', domain,
                '--email', email,
            ])
        }
    }
    if copy_to:
        commands.update({
            '2_certs_dest': {
                'command': 'mkdir -p ' + copy_to,
            },
            '3_copy_certs': {
                'cwd': copy_to,
                'command': Join('', [
                    'cp ' + conf_dir.rstrip('/') + '/live/', domain, '/*.pem .'
                ])
            },
        })
    return cf.InitConfig(
        'Certbot',
        files={
            script_name: {
                'source': 'https://dl.eff.org/certbot-auto',
                'mode': '000755',
                'owner': 'root',
                'group': 'root',
            },
            '/etc/cron.daily/certbot_renew': {
                'content': Join('', [
                    '#/bin/bash -e\n',
                    script_name + ' renew --config-dir ' + conf_dir,
                ]),
                'mode': '000755',
                'owner': 'root',
                'group': 'root',
            },
        },
        commands=commands
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

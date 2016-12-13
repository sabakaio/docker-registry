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


def htpasswd(filename):
    return cf.InitConfig(
        'htpasswd',
        files={
            filename: {
                'content': 'user:password_hash',
                'mode': '000660',
                'owner': 'root',
                'group': 'docker',
            },
        }
    )


def docker_compose(name, compose_yml):
    name = name.lower()
    compose_file = '/opt/{n}/docker-compose.yml'.format(n=name)
    init = cf.InitConfig(
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
    return init, compose_file


def certbot(domain, email, conf_dir='/opt/certs/', copy_to=None,
            pre_hook=None, post_hook=None):
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

    renew_script = [
        '#/bin/bash -e\n',
        'unset PYTHON_INSTALL_LAYOUT\n',
        script_name + ' renew --config-dir ' + conf_dir,
        ' --debug --non-interactive',
    ]
    if pre_hook:
        renew_script.append(' --pre-hook="' + pre_hook + '"')

    copy_certs = None
    if copy_to:
        copy_certs = Join('', [
            'cp ' + conf_dir.rstrip('/') + '/live/', domain, '/*.pem ', copy_to
        ])
        commands.update({
            '2_certs_dest': {
                'command': 'mkdir -p ' + copy_to,
            },
            '3_copy_certs': {
                'command': copy_certs,
            },
        })

    # Copy certificated and/or run a custop post-hook
    if copy_certs or post_hook:
        hook = [' --post-hook="']
        if copy_certs:
            hook.append(copy_certs)
        if post_hook:
            hook.extend([' && ', post_hook])
        hook.append('"')
        renew_script.append(hook)

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
                'content': Join('', renew_script),
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

from fabric.api import local

def prepare_deployment(branch_name):
    local('python ./manage.py test netmon')
    local('git add -p && git commit')
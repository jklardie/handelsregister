#!groovy

def tryStep(String message, Closure block, Closure tearDown = null) {
    try {
        block()
    }
    catch (Throwable t) {
        slackSend message: "${env.JOB_NAME}: ${message} failure ${env.BUILD_URL}", channel: '#ci-channel', color: 'danger'

        throw t
    }
    finally {
        if (tearDown) {
            tearDown()
        }
    }
}


node {
    stage("Checkout") {
        checkout scm
    }

    stage('Test') {
        tryStep "test", {
            sh "docker-compose -p handelsregister -f .jenkins-test/docker-compose.yml down"
            sh "docker-compose -p handelsregister -f .jenkins-test/docker-compose.yml build && " +
               "docker-compose -p handelsregister -f .jenkins-test/docker-compose.yml run -u root --rm tests"
        }, {
            sh "docker-compose -p handelsregister -f .jenkins-test/docker-compose.yml down"
        }
    }

    stage("Build image") {
        tryStep "build", {
            docker.withRegistry('https://repo.data.amsterdam.nl','docker-registry') {
                def image = docker.build("datapunt/handelsregister:${env.BUILD_NUMBER}", "web")
                image.push()
            }
        }
    }
}


String BRANCH = "${env.BRANCH_NAME}"

if (BRANCH == "master") {

    node {
        stage('Push acceptance image') {
            tryStep "image tagging", {
                docker.withRegistry('https://repo.data.amsterdam.nl','docker-registry') {
                    def image = docker.image("datapunt/handelsregister:${env.BUILD_NUMBER}")
                    image.pull()
                    image.push("acceptance")
                }
            }
        }
    }

    node {
        stage("Deploy to ACC") {
            tryStep "deployment", {
                build job: 'Subtask_Openstack_Playbook',
                parameters: [
                    [$class: 'StringParameterValue', name: 'INVENTORY', value: 'acceptance'],
                    [$class: 'StringParameterValue', name: 'PLAYBOOK', value: 'deploy-handelsregister.yml'],
                ]
            }
        }
    }

    stage('Waiting for approval') {
        slackSend channel: '#ci-channel', color: 'warning', message: 'Handelsregister is waiting for Production Release - please confirm'
        input "Deploy to Production?"
    }

    node {
        stage('Push production image') {
            tryStep "image tagging", {
                docker.withRegistry('https://repo.data.amsterdam.nl','docker-registry') {
                def image = docker.image("datapunt/handelsregister:${env.BUILD_NUMBER}")
                    image.pull()
                    image.push("production")
                    image.push("latest")
                }
            }
        }
    }

    node {
        stage("Deploy") {
            tryStep "deployment", {
                build job: 'Subtask_Openstack_Playbook',
                parameters: [
                    [$class: 'StringParameterValue', name: 'INVENTORY', value: 'production'],
                    [$class: 'StringParameterValue', name: 'PLAYBOOK', value: 'deploy-handelsregister.yml'],
                ]
            }
        }
    }
}

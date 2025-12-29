pipeline {
    agent {
        node {
            label 'built-in'
            customWorkspace '/home/opc/algo-deploy'
        }
    }
    environment {
        DOCKER_IMAGE = "algo-trader"
        DEPLOY_PATH = "/home/opc/algo-deploy"
    }
    stages {
        stage('Initialize') {
            steps {
                echo "🚀 Preparing Workspace..."
                checkout scm
                
                // Ensure permissions are always correct at start
                sh "sudo chown -R jenkins:jenkins ${DEPLOY_PATH}"
                
                echo "🧹 Cleaning Docker artifacts..."
                sh "docker builder prune -f"
                sh "docker image prune -f"
            }
        }
        stage('Prepare Secrets') {
            steps {
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    sh "cp -f \$SECRET_ENV ${DEPLOY_PATH}/.env"
                }
            }
        }
        stage('Build & Deploy') {
            steps {
                echo "📦 Building and Refreshing Containers..."
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
                sh "docker compose up -d --remove-orphans"
                sh "docker compose restart dashboard trading-bot"
            }
        }
    }
    post {
        always {
            // Scripting inside post always needs to be wrapped in script block or be simple
            script {
                try {
                    sh "docker image prune -f"
                } catch (Exception e) {
                    echo "Cleanup skipped: ${e.message}"
                }
            }
        }
    }
}
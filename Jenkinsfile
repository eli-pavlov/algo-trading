pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Sanitize Disk') {
            steps {
                echo "🧹 Cleaning Docker artifacts..."
                sh "docker builder prune -f"
                sh "docker image prune -f"
            }
        }
        stage('Checkout') {
            steps {
                cleanWs()
                checkout scm
            }
        }
        stage('Prepare Secrets') {
            steps {
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    // Wrap paths in single quotes to handle spaces in 'Alpaca Paper Trading'
                    sh "cp -f '${SECRET_ENV}' '${WORKSPACE}/.env'"
                }
            }
        }
        stage('Build & Deploy') {
            steps {
                echo "📦 Building and Refreshing..."
                // Use 'dir' to set the execution context to the workspace
                dir("${WORKSPACE}") {
                    sh """
                        export DOCKER_IMAGE=${DOCKER_IMAGE}
                        docker compose up -d --build --remove-orphans
                    """
                    sh "docker compose restart dashboard trading-bot"
                }
            }
        }
    }
    post {
        always {
            sh "docker image prune -f"
        }
    }
}
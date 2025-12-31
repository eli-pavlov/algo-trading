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
                dir("${WORKSPACE}") {
                    sh """
                        mkdir -p data config logs
                        export DOCKER_IMAGE=${DOCKER_IMAGE}
                        export WORKSPACE='${WORKSPACE}'
                        docker compose up -d --build --remove-orphans
                    """
                    // Changed 'dashboard' to 'dashboard' and 'trading-bot'
                    // These must match the keys in your docker-compose.yaml
                    sh "docker compose restart dashboard trading-bot"
                    sh "sleep 5"
                    sh "docker exec algo_heart python src/tuner.py"
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
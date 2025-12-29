pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('Prepare Secrets') {
            steps {
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    sh 'cp "$SECRET_ENV" .env'
                }
            }
        }
        stage('Build & Deploy') {
            steps {
                // We use --build-arg and --network host to bridge the connection gap
                sh "docker compose build --no-cache --pull --build-arg HTTP_PROXY='' --build-arg HTTPS_PROXY=''"
                
                // This is the key: manually building with host network if compose fails to bridge
                sh "docker build --network=host -t algo-trader-bot . "

                sh "docker compose up -d"
                
                sh "sleep 5"
                sh "docker exec algo_heart python src/analyzer.py"
                sh "docker image prune -f"
            }
        }
    }
}
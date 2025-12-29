pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
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
            // We tell docker to use the host network to avoid the SSL/DNS timeout issues
            sh "docker compose build --network=host"
            sh "docker compose up -d"
            sh "docker image prune -f"
        }
    }
    }
}
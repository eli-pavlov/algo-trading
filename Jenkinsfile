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
                // Use --no-cache once to clear out the broken pandas_ta attempts
                sh "docker compose build --no-cache"
                sh "docker compose up -d"
                sh "docker image prune -f"
            }
        }
    }
}
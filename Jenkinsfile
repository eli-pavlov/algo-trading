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
                // Use double quotes for Groovy to expand the variable correctly
                // And ensure the destination is clearly a file path
                sh "cp ${SECRET_ENV} .env"
            }
        }
    }
        stage('Build & Deploy') {
            steps {
                sh "docker compose build"
                sh "docker compose up -d"
                sh "docker image prune -f"
            }
        }
    }
}
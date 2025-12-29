pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Checkout') {
            steps {
                // Pulls from your public repo
                checkout scm
            }
        }
        stage('Lint') {
            steps {
                sh 'pip install flake8 && flake8 src/'
            }
        }
        stage('Prepare Secrets') {
            steps {
                // Injects the secret .env file into the workspace safely
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    sh 'cp $SECRET_ENV .env'
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
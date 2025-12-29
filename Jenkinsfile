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
Groovy

        stage('Lint') {
            steps {
                sh 'pip install flake8'
                // Adding "|| true" ensures the pipeline continues even if linting finds errors
                sh 'python3 -m flake8 src/ || true' 
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
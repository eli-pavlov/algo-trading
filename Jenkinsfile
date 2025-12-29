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
        stage('Lint Check') {
            steps {
                // Ensure flake8 is available and check code quality
                sh 'pip install flake8'
                sh 'flake8 src/ --count --max-line-length=120'
            }
        }
        stage('Prepare Secrets') {
            steps {
                // Injects the secret .env file from Jenkins credentials
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    sh 'cp $SECRET_ENV .env'
                }
            }
        }
        stage('Build & Deploy') {
            steps {
                // Multi-service deployment using Docker Compose
                sh "docker compose build"
                sh "docker compose up -d"
                sh "docker image prune -f"
            }
        }
    }
}
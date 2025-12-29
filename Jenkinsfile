pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/youruser/algo-trading.git'
            }
        }
        stage('Lint') {
            steps {
                sh 'pip install flake8 && flake8 src/'
            }
        }
        stage('Build & Deploy') {
            steps {
                // Docker Compose uses the local .env file which Jenkins should manage
                sh "docker compose build"
                sh "docker compose up -d"
            }
        }
    }
}
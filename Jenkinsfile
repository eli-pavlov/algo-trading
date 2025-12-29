pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Lint') {
            steps {
                sh 'pip install flake8 && flake8 src/'
            }
        }
        stage('Build & Deploy') {
            steps {
                sh "docker compose build"
                sh "docker compose up -d"
            }
        }
    }
}
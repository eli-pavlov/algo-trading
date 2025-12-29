pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Quality Gate') {
            steps {
                sh 'pip install flake8 && flake8 src/'
            }
        }
        stage('Build Image') {
            steps {
                sh "docker compose build"
            }
        }
        stage('Deploy') {
            steps {
                // Restarts the bot and UI with the new code
                sh "docker compose up -d"
            }
        }
    }
}
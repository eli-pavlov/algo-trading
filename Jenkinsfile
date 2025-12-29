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
                // FORCE network=host to bypass Jenkins 404/Stapler proxy issues
                sh "docker compose build --no-cache --pull"
                sh "docker compose up -d"
                
                // Give the container 5 seconds to wake up before running analyzer
                sh "sleep 5"
                sh "docker exec algo_heart python src/analyzer.py"
                
                sh "docker image prune -f"
            }
        }
    }
}
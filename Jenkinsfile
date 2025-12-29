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
                // 1. Build the images
                sh "docker compose build"
                
                // 2. Start the containers
                sh "docker compose up -d"
                
                // 3. WAIT & RETRAIN (Run Analyzer inside the active container)
                // We run it as a background-safe command to ensure DB is populated
                sh "docker exec algo_heart python src/analyzer.py"
                
                // 4. Cleanup old images
                sh "docker image prune -f"
            }
        }
    }
}
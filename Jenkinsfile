pipeline {
    agent any
    environment {
        // This variable isn't strictly needed anymore but good for reference
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
                // 1. Build the image using HOST networking
                // This allows pip to connect to PyPI successfully (like your manual test)
                sh "docker build --network=host -t algo-trader ."

                // 2. Start containers using the image we just built
                // We remove orphans to clean up any old containers from previous failed builds
                sh "docker compose up -d --remove-orphans"
                
                // 3. Wait for boot and Train
                sh "sleep 5"
                sh "docker exec algo_heart python src/analyzer.py"
                
                // 4. Cleanup dangling images to save disk space
                sh "docker image prune -f"
            }
        }
    }
}
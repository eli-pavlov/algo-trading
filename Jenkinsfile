pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Disk Cleanup') {
            steps {
                echo "🧹 Cleaning OCI Disk Space..."
                // Prune builder cache specifically to free up space for pip
                sh "docker builder prune -f"
                // Remove images older than 24h
                sh "docker image prune -a --filter 'until=24h' -f"
            }
        }
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
        
        // STAGE: Build Image
        // Only runs if core files change or if the image is missing
        stage('Build Image') {
            when {
                anyOf {
                    changeset "requirements.txt"
                    changeset "Dockerfile"
                    changeset "Jenkinsfile"
                    // Force build if image doesn't exist locally
                    expression { sh(script: "docker images -q ${DOCKER_IMAGE} == ''", returnStatus: true) == 0 }
                }
            }
            steps {
                echo "📦 Core files changed. Rebuilding Docker Image..."
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
            }
        }

        // STAGE: Deploy & Refresh Logic
        stage('Deploy & Refresh') {
            steps {
                echo "🚀 Syncing logic and restarting containers..."
                
                // 'up -d' ensures the network and base containers are correct
                sh "docker compose up -d --remove-orphans"
                
                // CRITICAL: Restarting the bot service forces Python to reload 
                // the new logic mapped from the host disk.
                sh "docker compose restart trading-bot"
                
                sh "sleep 5"
                sh "docker exec algo_heart python src/tuner.py"
                sh "docker image prune -f"
            }
        }
    }
}
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
        
        // --- STAGE A: Build Image (Only if dependencies changed) ---
        stage('Build Image') {
            when {
                anyOf {
                    changeset "requirements.txt"
                    changeset "Dockerfile"
                    changeset "Jenkinsfile"
                    // If the image doesn't exist at all, we must build it
                    expression { sh(script: "docker images -q ${DOCKER_IMAGE} == ''", returnStatus: true) == 0 }
                }
            }
            steps {
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
            }
        }

        // --- STAGE B: Deploy & Update Logic ---
        stage('Deploy & Refresh') {
            steps {
                // Because of the 'volumes' in docker-compose.yaml, 
                // simply running 'up -d' will pick up new .py files immediately.
                sh "docker compose up -d --remove-orphans"
                
                // If the container was already running, it needs a restart 
                // to refresh the Python process memory with the new logic.
                sh "docker compose restart trading-bot"
                
                sh "sleep 5"
                sh "docker exec algo_heart python src/tuner.py"
                sh "docker image prune -f"
            }
        }
    }
}
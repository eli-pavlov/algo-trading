pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Sanitize Disk') {
            steps {
                echo "🧹 Cleaning Docker only (Safe Cleanup)..."
                sh "docker builder prune -f"
                sh "docker image prune -f"
                // REMOVED: sudo rm -rf /var/lib/jenkins/workspace/* // That line was the "Workspace Eraser" causing your error.
            }
        }
        stage('Checkout') {
            steps { 
                cleanWs()
                checkout scm }
        }
        stage('Prepare Secrets') {
            steps {
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    // Added -f to force overwrite and ensure permissions are fresh
                    sh 'cp -f "$SECRET_ENV" .env'
                }
            }
        }
        stage('Build Image') {
            when {
                anyOf {
                    changeset "requirements.txt"
                    changeset "Dockerfile"
                    expression { sh(script: "docker images -q ${DOCKER_IMAGE} == ''", returnStatus: true) == 0 }
                }
            }
            steps {
                echo "📦 Building Docker Image..."
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
            }
        }
        stage('Deploy & Refresh') {
            steps {
                echo "🚀 Deploying Logic..."
                sh "docker compose up -d --remove-orphans"
                // Forces the bot to reload the python code from the bind mount
                sh "docker compose restart trading-bot"
                sh "sleep 5"
                // Check if heart is alive before tuning
                sh "docker exec algo_heart python src/tuner.py"
            }
        }
    }
    post {
        always {
            // Reclaim space immediately after every build
            sh "docker image prune -f"
        }
    }
}
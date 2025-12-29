pipeline {
    agent any
    environment {
        DOCKER_IMAGE = "algo-trader"
    }
    stages {
        stage('Sanitize Disk') {
            steps {
                echo "🧹 Pruning Docker caches to free up space..."
                // Removes the specific Buildx state that was taking 2.6GB
                sh "docker builder prune -f"
                // Removes unused images and dangling layers
                sh "docker image prune -f"
                // Clear system logs older than 1 day to prevent /var/log bloat
                sh "sudo journalctl --vacuum-time=1d || true"
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
        stage('Build Image') {
            when {
                anyOf {
                    changeset "requirements.txt"
                    changeset "Dockerfile"
                    expression { sh(script: "docker images -q ${DOCKER_IMAGE} == ''", returnStatus: true) == 0 }
                }
            }
            steps {
                // Using --no-cache here is safer when disk is tight to prevent partial layer bloat
                sh "docker build --network=host --no-cache -t ${DOCKER_IMAGE} ."
            }
        }
        stage('Deploy & Refresh') {
            steps {
                sh "docker compose up -d --remove-orphans"
                sh "docker compose restart trading-bot"
                sh "sleep 5"
                sh "docker exec algo_heart python src/tuner.py"
            }
        }
    }
    post {
        success {
            echo "✅ Build Successful. Final cleanup..."
            sh "docker image prune -f"
        }
    }
}
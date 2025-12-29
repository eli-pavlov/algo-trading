pipeline {
    agent {
        node {
            label 'built-in'
            // FORCES a fixed, clean path on your OCI disk
            customWorkspace '/home/opc/algo-deploy'
        }
    }
    environment {
        DOCKER_IMAGE = "algo-trader"
        DEPLOY_PATH = "/home/opc/algo-deploy"
    }
    stages {
        stage('Initialize') {
            steps {
                echo "🚀 Initializing Fixed Workspace at ${DEPLOY_PATH}"
                checkout scm
                
                // Fix the root-owned folders from previous manual runs
                sh "sudo chown -R jenkins:jenkins ${DEPLOY_PATH}"
                
                echo "🧹 Pre-build cleanup..."
                sh "docker builder prune -f"
                sh "docker image prune -f"
            }
        }
        stage('Prepare Secrets') {
            steps {
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    sh "cp -f \$SECRET_ENV ${DEPLOY_PATH}/.env"
                }
            }
        }
        stage('Build & Deploy') {
            steps {
                echo "📦 Building and Refreshing Containers..."
                // Build the image
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
                
                // Deploy using the fixed path for volumes
                sh "docker compose up -d --remove-orphans"
                
                // Force reload of Python files from the fixed mount
                sh "docker compose restart dashboard trading-bot"
            }
        }
        stage('Post-Deploy Tuning') {
            steps {
                echo "🎯 Running Strategy Tuner..."
                sh "docker exec algo_heart python src/tuner.py"
            }
        }
    }
    post {
        always {
            sh "docker image prune -f"
        }
    }
}
pipeline {
    agent {
        node {
            label 'built-in'
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
                echo "🚀 Preparing Workspace..."
                checkout scm
                
                // Absolute safety: ensure jenkins owns everything it just checked out
                sh "sudo chown -R jenkins:jenkins ${DEPLOY_PATH}"
                
                echo "🧹 Pruning Docker Caches..."
                sh "docker builder prune -f"
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
                echo "📦 Building Image..."
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
                
                echo "🚢 Launching Containers..."
                sh "docker compose up -d --remove-orphans"
                
                // Force restart to refresh the Python code mounted from the disk
                sh "docker compose restart dashboard trading-bot"
                
                echo "🎯 Running Auto-Tuner..."
                sh "docker exec algo_heart python src/tuner.py"
            }
        }
    }
    post {
        always {
            // Re-wrapping in node to avoid context errors
            node('built-in') {
                script {
                    sh "docker image prune -f"
                }
            }
        }
    }
}
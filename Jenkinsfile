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
                echo "🚀 Preparing Workspace at ${DEPLOY_PATH}..."
                checkout scm
                
                // Ensure Jenkins maintains ownership
                sh "sudo chown -R jenkins:jenkins ${DEPLOY_PATH}"
                
                echo "🧹 Pruning Docker Build Cache..."
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
                echo "📦 Building Image & Starting Containers..."
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
                sh "docker compose up -d --remove-orphans"
                
                echo "🔄 Restarting services to pick up code changes..."
                sh "docker compose restart dashboard trading-bot"
                
                echo "🎯 Running Strategy Tuner..."
                sh "docker exec algo_heart python src/tuner.py"
            }
        }
    }
    post {
        always {
            node('built-in') {
                script {
                    sh "docker image prune -f"
                }
            }
        }
    }
}
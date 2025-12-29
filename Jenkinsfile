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
                echo "🚀 Preparing Fixed Workspace..."
                checkout scm
                
                // Keep permissions clean every build
                sh "sudo chown -R jenkins:jenkins ${DEPLOY_PATH}"
                
                echo "🧹 Pruning Docker..."
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
                echo "📦 Compiling and Launching..."
                sh "docker build --network=host -t ${DOCKER_IMAGE} ."
                sh "docker compose up -d --remove-orphans"
                sh "docker compose restart dashboard trading-bot"
                
                echo "🎯 Running Auto-Tuner..."
                sh "docker exec algo_heart python src/tuner.py"
            }
        }
    }
    post {
        always {
            // Ensure cleanup runs inside a node context
            node('built-in') {
                sh "docker image prune -f"
            }
        }
    }
}
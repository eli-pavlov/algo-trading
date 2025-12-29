pipeline {
    agent any
    options {
        // This prevents the creation of 'Alpaca Paper Trading@2'
        skipDefaultCheckout() 
    }
    environment {
        DOCKER_IMAGE = "algo-trader"
        // Get the absolute path of the current workspace
        WS_PATH = "${WORKSPACE}" 
    }
    stages {
        stage('Initialize & Cleanup') {
            steps {
                // Manually check out to the fixed workspace
                checkout scm
                echo "🧹 Cleaning up old Docker artifacts..."
                sh "docker builder prune -f"
                sh "docker image prune -f"
                // Ensure Jenkins owns everything before we start
                sh "sudo chown -R jenkins:jenkins ${WS_PATH}"
            }
        }
        stage('Prepare Secrets') {
            steps {
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    sh "cp -f \$SECRET_ENV ${WS_PATH}/.env"
                }
            }
        }
        stage('Build & Deploy') {
            steps {
                dir("${WS_PATH}") {
                    echo "📦 Building and Restarting..."
                    sh "docker build --network=host -t ${DOCKER_IMAGE} ."
                    
                    // We use the absolute path for the volume mapping to be 100% safe
                    sh "DOCKER_IMAGE=${DOCKER_IMAGE} WS_PATH=${WS_PATH} docker compose up -d --remove-orphans"
                    sh "docker compose restart dashboard trading-bot"
                }
            }
        }
    }
}
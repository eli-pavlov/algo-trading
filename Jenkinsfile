pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = "algo-trader"
    }

    stages {
        stage('Build') {
            steps {
                sh 'docker build -t ${DOCKER_IMAGE}:${BRANCH_NAME} .'
            }
        }

        stage('Deploy Staging') {
            when { branch 'dev' }
            steps {
                withCredentials([string(credentialsId: 'alpaca-paper-key', variable: 'KEY'),
                                 string(credentialsId: 'alpaca-paper-secret', variable: 'SECRET')]) {
                    sh '''
                        docker stop bot-staging || true
                        docker rm bot-staging || true
                        docker run -d --name bot-staging --restart always \
                            -e ALPACA_API_KEY=$KEY \
                            -e ALPACA_SECRET_KEY=$SECRET \
                            -e ALPACA_BASE_URL="https://paper-api.alpaca.markets" \
                            -e TRADING_MODE="PAPER" \
                            -v $PWD/config:/app/config \
                            ${DOCKER_IMAGE}:${BRANCH_NAME}
                    '''
                }
            }
        }

        stage('Deploy Production') {
            when { branch 'main' }
            steps {
                withCredentials([string(credentialsId: 'alpaca-live-key', variable: 'KEY'),
                                 string(credentialsId: 'alpaca-live-secret', variable: 'SECRET')]) {
                    sh '''
                        docker stop bot-prod || true
                        docker rm bot-prod || true
                        docker run -d --name bot-prod --restart always \
                            -e ALPACA_API_KEY=$KEY \
                            -e ALPACA_SECRET_KEY=$SECRET \
                            -e ALPACA_BASE_URL="https://api.alpaca.markets" \
                            -e TRADING_MODE="LIVE" \
                            -v $PWD/config:/app/config \
                            ${DOCKER_IMAGE}:${BRANCH_NAME}
                    '''
                }
            }
        }
    }
}
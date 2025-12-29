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
        stage('Build & Deploy') {
            steps {
                // 1. Manually build the image using the host network (the part that worked manually)
                // We tag it as 'algo-trader' so docker-compose can find it
                sh "docker build --network=host -t algo-trader-image . "

                // 2. Start the containers
                // We use --no-build to ensure it uses the image we just created
                sh "docker compose up -d"
                
                // 3. RETRAIN
                sh "sleep 5"
                sh "docker exec algo_heart python src/analyzer.py"
                
                // 4. Cleanup
                sh "docker image prune -f"
            }
        }
    }
}
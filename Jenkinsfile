pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        // Lint stage is GONE - handled by GitHub
        stage('Prepare Secrets') {
            steps {
                withCredentials([file(credentialsId: 'algo-trading-env', variable: 'SECRET_ENV')]) {
                    sh 'cp $SECRET_ENV .env'
                }
            }
        }
        stage('Build & Deploy') {
            steps {
                sh "docker compose up --build -d"
            }
        }
    }
}
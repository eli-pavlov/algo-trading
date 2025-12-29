pipeline {
    agent any
    
    environment {
        // Points to the .env file on the Jenkins server for security
        ENV_FILE = credentials('algo-trading-env') 
    }

    stages {
        stage('🛠️ Build') {
            steps {
                echo 'Building Docker Images...'
                sh 'docker compose build'
            }
        }

        stage('🛡️ Quality Check') {
            steps {
                echo 'Running Linting...'
                // Runs flake8 inside the newly built container
                sh 'docker compose run --rm trading-bot flake8 src/'
            }
        }

        stage('🚀 Deploy') {
            steps {
                echo 'Restarting Services...'
                // -d runs it in the background (daemon mode)
                sh 'docker compose up -d'
            }
        }

        stage('🧹 Cleanup') {
            steps {
                echo 'Cleaning up dangling images...'
                sh 'docker image prune -f'
            }
        }
    }
}
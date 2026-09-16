pipeline {
    agent any

    environment {
        IMAGE_NAME = "userapi"
        IMAGE_TAG = "${BUILD_NUMBER}"
        CONTAINER_NAME = "userapi-ci"
        APP_PORT = "5000"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r app/requirements.txt
                    pip install -r app/requirements-dev.txt
                    python -m py_compile app/app.py
                '''
            }
        }

        stage('Automated Tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest tests/ -v
                '''
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build \
                      -t ${IMAGE_NAME}:${IMAGE_TAG} \
                      ./app
                '''
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    docker rm -f ${CONTAINER_NAME} 2>/dev/null || true

                    docker run -d \
                      --name ${CONTAINER_NAME} \
                      -p ${APP_PORT}:5000 \
                      -e DATABASE_PATH=/data/app.db \
                      -e PORT=5000 \
                      ${IMAGE_NAME}:${IMAGE_TAG}

                    sleep 3
                '''
            }
        }

        stage('Smoke Test') {
            steps {
                sh '''
                    for i in 1 2 3 4 5
                    do
                        if curl -sf http://localhost:${APP_PORT}/health
                        then
                            echo "Health check passed"
                            break
                        fi

                        echo "Retry $i..."
                        sleep 2
                    done

                    curl -sf http://localhost:${APP_PORT}/health
                    curl -sf http://localhost:${APP_PORT}/users

                    echo "Smoke tests passed"
                '''
            }
        }
    }

    post {
        always {
            sh '''
                docker rm -f ${CONTAINER_NAME} 2>/dev/null || true
            '''
        }
    }
}

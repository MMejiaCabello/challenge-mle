#!/usr/bin/env bash

set -Eeuo pipefail

SERVICE_NAME="${SERVICE_NAME:-challenge-mle}"
PROJECT_ID="${PROJECT_ID:-dev-farma-analytics-workspace}"
REGION="${REGION:-us-central1}"

if ! command -v gcloud >/dev/null 2>&1; then
    echo "Error: gcloud no está instalado o no está disponible en PATH." >&2
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "Error: curl no está instalado o no está disponible en PATH." >&2
    exit 1
fi

if [[ ! -f Dockerfile ]]; then
    echo "Error: ejecuta este script desde la raíz del repositorio." >&2
    exit 1
fi

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
    echo "Error: configura un proyecto con 'gcloud config set project PROJECT_ID'" >&2
    echo "       o ejecuta el script con PROJECT_ID=PROJECT_ID ./deploy.sh" >&2
    exit 1
fi

echo "Desplegando ${SERVICE_NAME} en ${PROJECT_ID} (${REGION})..."

gcloud run deploy "${SERVICE_NAME}" \
    --source . \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --concurrency 20 \
    --min-instances 0 \
    --max-instances 3 \
    --no-invoker-iam-check \
    --quiet

SERVICE_URL="$(
    gcloud run services describe "${SERVICE_NAME}" \
        --project "${PROJECT_ID}" \
        --region "${REGION}" \
        --format='value(status.url)'
)"

if [[ -z "${SERVICE_URL}" ]]; then
    echo "Error: Cloud Run no devolvió la URL del servicio." >&2
    exit 1
fi

echo "Verificando ${SERVICE_URL}/health..."
if ! curl --fail --silent --show-error "${SERVICE_URL}/health"; then
    printf '\n' >&2
    echo "Error: el servicio fue desplegado, pero /health no permite acceso público." >&2
    echo "Verifica que tu usuario tenga el permiso run.services.setIamPolicy." >&2
    exit 1
fi
printf '\n'

echo "Despliegue completado: ${SERVICE_URL}"
echo "Prueba de estrés: make stress-test STRESS_URL=${SERVICE_URL}"

#!/bin/bash

# Test de l'API Widget IA Grist avec le nouveau format
# Port: 8502 (comme configuré dans main.py)
# Le JSON est maintenant envoyé directement comme body, les headers sont dans les headers HTTP

curl -X POST http://localhost:8502/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: b3d3330322f4c738bcfb596b87d362d72cb242c5" \
  -H "User-Agent: node" \
  -H "Accept: */*" \
  -H "Accept-Language: *" \
  -d '{
    "documentId": "maBberfz12MHTDGAS9ZFHn",
    "messages": [
      {
        "id": "69f93b02-ccfc-41a2-a650-f65ee35b34c9",
        "createdAt": "2025-06-03T10:37:43.096Z",
        "role": "user",
        "content": "Bonjour ! Peux-tu m'\''aider à analyser les données de ce document Grist ?",
        "parts": [
          {
            "type": "text",
            "text": "Bonjour ! Peux-tu m'\''aider à analyser les données de ce document Grist ?"
          }
        ]
      },
      {
        "id": "b55bded0-b0d0-4bf1-982c-b7bfba5653a1",
        "createdAt": "2025-06-03T10:37:44.384Z",
        "role": "assistant",
        "content": "Bien sûr ! Je suis là pour vous aider à analyser vos données Grist. Que souhaitez-vous savoir ?",
        "parts": [
          {
            "type": "text",
            "text": "Bien sûr ! Je suis là pour vous aider à analyser vos données Grist. Que souhaitez-vous savoir ?"
          }
        ]
      },
      {
        "id": "8f67159d-8ab6-4837-8f91-22bfa5936e10",
        "createdAt": "2025-06-03T10:37:47.142Z",
        "role": "user",
        "content": "Bonjour",
        "parts": [
          {
            "type": "text",
            "text": "Bonjour"
          }
        ]
      }
    ],
    "webhookUrl": "https://./webhook/chat",
    "executionMode": "production"
  }' 
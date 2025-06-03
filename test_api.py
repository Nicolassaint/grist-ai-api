#!/usr/bin/env python3
"""
Script de test simple pour l'API Widget IA Grist
"""

import requests
import json
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# Configuration
PORT = os.getenv("PORT", "8000")
API_BASE_URL = f"http://localhost:{PORT}"

def test_root_endpoint():
    """Test de l'endpoint racine"""
    print("🧪 Test de l'endpoint racine...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_health_endpoint():
    """Test de l'endpoint de santé"""
    print("\n🧪 Test de l'endpoint de santé...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_agents_endpoint():
    """Test de l'endpoint des agents"""
    print("\n🧪 Test de l'endpoint des agents...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/agents")
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_chat_endpoint():
    """Test de l'endpoint de chat"""
    print("\n🧪 Test de l'endpoint de chat...")
    
    # Données de test selon le format attendu
    test_request = [
        {
            "headers": {
                "x-api-key": "test-grist-key"
            },
            "params": {},
            "query": {},
            "body": {
                "documentId": "test-document-id",
                "messages": [
                    {
                        "role": "user",
                        "content": "Bonjour, comment ça va ?"
                    }
                ],
                "webhookUrl": "https://example.com/webhook/chat",
                "executionMode": "production"
            }
        }
    ]
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json=test_request,
            headers={"Content-Type": "application/json"}
        )
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_stats_endpoint():
    """Test de l'endpoint des statistiques"""
    print("\n🧪 Test de l'endpoint des statistiques...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/stats")
        print(f"✅ Status: {response.status_code}")
        print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🚀 Démarrage des tests de l'API Widget IA Grist")
    print("=" * 60)
    
    tests = [
        test_root_endpoint,
        test_health_endpoint,
        test_agents_endpoint,
        test_stats_endpoint,
        test_chat_endpoint  # Test du chat en dernier car il peut échouer si pas de config
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        if test_func():
            passed += 1
        print("-" * 40)
    
    print(f"\n📊 Résultats: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés !")
    else:
        print("⚠️  Certains tests ont échoué. Vérifiez la configuration.")

if __name__ == "__main__":
    main() 
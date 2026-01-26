"""
SYSTÈME FINAL : EMAIL AUTO RESPONDER AVEC ENVOI AUTOMATIQUE
=============================================================
Lit, analyse ET envoie automatiquement les réponses !

NOUVELLES FONCTIONNALITÉS :
✅ Envoi automatique des réponses
✅ Confirmation avant envoi
✅ Extraction intelligente du destinataire
✅ Réponse dans le même thread
"""

from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os
import sys
import re

# Importer le module Gmail (AVEC fonction send_email)
from fix import GmailConnector

load_dotenv()

print("\n" + "="*80)
print("🤖 EMAIL AUTO RESPONDER - AVEC ENVOI AUTOMATIQUE")
print("="*80 + "\n")

# ========================================
# CRÉATION DES AGENTS
# ========================================

print("📋 Initialisation des agents IA...\n")

agent_lecteur = Agent(
    role="Email Information Extractor",
    goal="Extraire et structurer toutes les informations clés d'un email",
    backstory="""Vous êtes un expert en analyse de contenu. Vous identifiez 
    rapidement l'expéditeur, le sujet principal, les demandes formulées, 
    et les informations de contact importantes.""",
    llm="claude-3-haiku-20240307",
    verbose=False
)

agent_classificateur = Agent(
    role="Email Priority Analyst",
    goal="Classifier les emails selon leur type, urgence et priorité",
    backstory="""Vous êtes un analyste expert qui évalue les emails selon 
    plusieurs critères : type de demande, niveau d'urgence, sentiment, 
    et actions requises. Votre classification aide à prioriser les réponses.""",
    llm="claude-3-haiku-20240307",
    verbose=False
)

agent_repondeur = Agent(
    role="Professional Response Writer",
    goal="Créer des réponses email professionnelles, personnalisées et complètes",
    backstory="""Vous êtes un expert en communication professionnelle. 
    Vous rédigez des réponses qui sont à la fois courtoises, claires, 
    et adaptées au contexte. Vous tenez compte de l'urgence et du ton 
    approprié pour chaque situation.""",
    llm="claude-3-haiku-20240307",
    verbose=False
)

print("   ✅ 3 agents créés avec succès\n")

# ========================================
# FONCTION POUR PARSER LA RÉPONSE
# ========================================

def parser_reponse(reponse_brute):
    """
    Extrait l'objet et le corps de la réponse générée
    
    Args:
        reponse_brute (str): Réponse complète de l'agent
        
    Returns:
        tuple: (objet, corps)
    """
    lignes = str(reponse_brute).split('\n')
    objet = ""
    corps_lignes = []
    corps_commence = False
    
    for ligne in lignes:
        # Chercher l'objet
        if ligne.strip().upper().startswith('OBJET:') or ligne.strip().upper().startswith('SUBJECT:'):
            objet = ligne.split(':', 1)[1].strip()
        # Chercher le corps
        elif ligne.strip().upper().startswith('CORPS:') or ligne.strip().upper().startswith('BODY:'):
            corps_commence = True
        elif corps_commence and ligne.strip():
            corps_lignes.append(ligne)
    
    # Si pas d'objet trouvé, utiliser un par défaut
    if not objet:
        objet = "Re: Votre message"
    
    # Si pas de corps trouvé, utiliser toute la réponse
    if not corps_lignes:
        corps = str(reponse_brute)
    else:
        corps = '\n'.join(corps_lignes)
    
    return objet, corps

# ========================================
# FONCTION DE TRAITEMENT D'UN EMAIL
# ========================================

def traiter_email(email_data):
    """Traite un email avec les 3 agents"""
    
    email_texte = f"""
De: {email_data['from']}
À: {email_data['to']}
Objet: {email_data['subject']}
Date: {email_data['date']}

Corps:
{email_data['body'][:1000]}
"""
    
    # TÂCHE 1 : Extraction
    tache_lecture = Task(
        description=f"""
        Extrayez les informations clés de cet email :
        
        {email_texte}
        
        Fournissez :
        1. Expéditeur (nom et email)
        2. Sujet principal
        3. Résumé du contenu (2-3 phrases)
        4. Demandes ou questions posées
        5. Informations de contact mentionnées
        """,
        expected_output="Rapport structuré avec toutes les informations extraites",
        agent=agent_lecteur
    )
    
    # TÂCHE 2 : Classification
    tache_classification = Task(
        description="""
        Classifiez cet email :
        
        Déterminez :
        1. TYPE : demande_info, support_technique, commercial, recrutement, spam, autre
        2. URGENCE : critique, haute, moyenne, basse
        3. PRIORITÉ : P1, P2, P3, P4
        4. SENTIMENT : positif, neutre, négatif
        5. DÉLAI DE RÉPONSE : immédiat, 2h, 24h, 48h
        """,
        expected_output="Classification complète avec justifications",
        agent=agent_classificateur,
        context=[tache_lecture]
    )
    
    # TÂCHE 3 : Génération de réponse
    tache_reponse = Task(
        description="""
        Rédigez une réponse professionnelle pour cet email.
        
        La réponse doit :
        - Être adaptée à l'urgence et au type d'email
        - Répondre à toutes les questions/demandes
        - Être courtoise et professionnelle
        - Inclure un objet de réponse approprié
        
        Format STRICT :
        OBJET: [objet de la réponse]
        
        CORPS:
        [corps de l'email de réponse]
        """,
        expected_output="Email de réponse complet prêt à envoyer",
        agent=agent_repondeur,
        context=[tache_lecture, tache_classification]
    )
    
    # Créer le crew et exécuter
    crew = Crew(
        agents=[agent_lecteur, agent_classificateur, agent_repondeur],
        tasks=[tache_lecture, tache_classification, tache_reponse],
        verbose=False
    )
    
    resultat = crew.kickoff()
    
    # Parser la réponse pour extraire objet et corps
    objet, corps = parser_reponse(resultat)
    
    return {
        'email_id': email_data['id'],
        'thread_id': email_data['thread_id'],
        'message_id_header': email_data['message_id_header'],
        'from': email_data['from'],
        'subject': email_data['subject'],
        'response_subject': objet,
        'response_body': corps,
        'response_full': str(resultat)
    }

# ========================================
# FONCTION PRINCIPALE
# ========================================

def main():
    """Fonction principale du système"""
    
    # 1. Connexion à Gmail
    print("🔐 Connexion à Gmail...\n")
    gmail = GmailConnector()
    
    if not gmail.authenticate():
        print("❌ Échec de l'authentification Gmail")
        return
    
    # 2. Récupérer les emails non lus
    print("📬 Recherche d'emails non lus...\n")
    emails = gmail.get_unread_emails(max_results=3)
    
    if not emails:
        print("✅ Aucun email non lu à traiter")
        print("\n💡 Conseil : Marquez quelques emails comme non lus pour tester le système\n")
        return
    
    print(f"📨 {len(emails)} email(s) à traiter\n")
    print("="*80 + "\n")
    
    # 3. Traiter chaque email
    resultats = []
    
    for i, email in enumerate(emails, 1):
        print(f"🔄 TRAITEMENT DE L'EMAIL #{i}/{len(emails)}")
        print("-"*80)
        print(f"De      : {email['from']}")
        print(f"Objet   : {email['subject']}")
        print(f"Date    : {email['date']}")
        print("-"*80)
        
        print("\n⏳ Analyse par les agents IA (30-60 secondes)...\n")
        
        try:
            resultat = traiter_email(email)
            resultats.append(resultat)
            
            print("✅ Analyse terminée !\n")
            print("="*80)
            print("📝 RÉPONSE GÉNÉRÉE :")
            print("="*80)
            print(f"OBJET: {resultat['response_subject']}")
            print(f"\nCORPS:\n{resultat['response_body']}")
            print("="*80 + "\n")
            
        except Exception as e:
            print(f"❌ Erreur lors du traitement : {e}\n")
            continue
    
    # 4. Résumé final
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DE LA SESSION")
    print("="*80)
    print(f"Emails traités    : {len(resultats)}/{len(emails)}")
    print(f"Réponses générées : {len(resultats)}")
    print("="*80 + "\n")
    
    if not resultats:
        return
    
    # ========================================
    # 5. ENVOI AUTOMATIQUE DES RÉPONSES
    # ========================================
    
    print("="*80)
    print("📧 ENVOI DES RÉPONSES")
    print("="*80 + "\n")
    
    print("💡 Voulez-vous envoyer les réponses automatiquement ? (o/n) : ", end="")
    choix = input().strip().lower()
    
    if choix in ['o', 'oui', 'y', 'yes']:
        print("\n🚀 Envoi des réponses en cours...\n")
        
        for resultat in resultats:
            print(f"📤 Envoi de la réponse à : {resultat['from']}")
            
            # Extraire l'adresse email du header From
            destinataire = gmail.extract_email_address(resultat['from'])
            
            # Envoyer l'email
            sent = gmail.send_email(
                to=destinataire,
                subject=resultat['response_subject'],
                body=resultat['response_body'],
                reply_to_message_id=resultat['message_id_header'],
                thread_id=resultat['thread_id']
            )
            
            if sent:
                # Marquer comme lu
                gmail.mark_as_read(resultat['email_id'])
                print(f"   ✅ Réponse envoyée et email marqué comme lu\n")
            else:
                print(f"   ❌ Échec de l'envoi\n")
        
        print("="*80)
        print("✅ Tous les emails ont été traités !")
        print("="*80 + "\n")
    
    else:
        print("\n📋 Aucun email envoyé. Les réponses sont disponibles ci-dessus.\n")
        
        # Option de marquage comme lu
        print("💡 Voulez-vous marquer ces emails comme lus ? (o/n) : ", end="")
        choix_lu = input().strip().lower()
        
        if choix_lu in ['o', 'oui', 'y', 'yes']:
            print("\n🔄 Marquage des emails comme lus...\n")
            for resultat in resultats:
                gmail.mark_as_read(resultat['email_id'])
            print("✅ Emails marqués comme lus\n")
    
    print("🎉 Session terminée avec succès !\n")
    print("="*80)
    print("💡 FONCTIONNALITÉS ACTIVES :")
    print("="*80)
    print("✅ Lecture automatique des emails")
    print("✅ Analyse par 3 agents IA")
    print("✅ Génération de réponses")
    print("✅ ENVOI AUTOMATIQUE DES EMAILS")
    print("✅ Marquage comme lu")
    print("="*80 + "\n")

# ========================================
# POINT D'ENTRÉE
# ========================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Arrêt du programme par l'utilisateur\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur fatale : {e}\n")
        sys.exit(1)
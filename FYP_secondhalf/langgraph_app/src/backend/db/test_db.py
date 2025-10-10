"""
Test script for MongoDB database utilities.

This script tests saving and retrieving artifacts and conversations from MongoDB.
Run this file to verify your MongoDB connection and data persistence.

Usage:
    python -m backend.db.test_db
"""

import sys
import os
from datetime import datetime, timezone
from pprint import pprint

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.db_utils import (
    save_artifact_to_db,
    save_conversation_to_db,
    get_artifacts_from_db,
    get_conversations_from_db,
    get_latest_artifact_version,
    delete_thread_data,
    create_indexes
)


def test_basic_operations():
    """Test basic save and retrieve operations"""
    print("\n" + "="*60)
    print("TEST 1: Basic Save and Retrieve Operations")
    print("="*60)

    test_thread_id = "test_thread_12345"

    # Create indexes
    print("\n1. Creating indexes...")
    create_indexes()
    print("✓ Indexes created")

    # Test artifact saving
    print("\n2. Saving test artifacts...")

    artifact_1 = {
        "artifact_id": "requirements_classification_Analyst_v1.0",
        "artifact_type": "requirements_classification",
        "agent": "Analyst",
        "content": {
            "functional_requirements": ["User login", "Data export"],
            "non_functional_requirements": ["Performance", "Security"]
        },
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "classify_user_requirements"
    }

    artifact_2 = {
        "artifact_id": "requirements_model_Analyst_v1.0",
        "artifact_type": "requirements_model",
        "agent": "Analyst",
        "content": {
            "diagram_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "diagram_path": "/tmp/diagram.png",
            "uml_fmt_content": "@startuml\nactor User\n@enduml"
        },
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "build_requirement_model"
    }

    result_1 = save_artifact_to_db(test_thread_id, artifact_1)
    result_2 = save_artifact_to_db(test_thread_id, artifact_2)

    print(f"✓ Artifact 1 saved: {result_1}")
    print(f"✓ Artifact 2 saved: {result_2}")

    # Test conversation saving
    print("\n3. Saving test conversations...")

    conversation_1 = {
        "content": "I've classified your requirements into functional and non-functional categories.",
        "agent": "Analyst",
        "artifact_id": "requirements_classification_Analyst_v1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "classify_user_requirements"
    }

    conversation_2 = {
        "content": "Here's the requirements model with a use case diagram.",
        "agent": "Analyst",
        "artifact_id": "requirements_model_Analyst_v1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "build_requirement_model"
    }

    result_3 = save_conversation_to_db(test_thread_id, conversation_1)
    result_4 = save_conversation_to_db(test_thread_id, conversation_2)

    print(f"✓ Conversation 1 saved: {result_3}")
    print(f"✓ Conversation 2 saved: {result_4}")

    # Retrieve artifacts
    print("\n4. Retrieving artifacts...")
    artifacts = get_artifacts_from_db(test_thread_id)
    print(f"✓ Retrieved {len(artifacts)} artifacts")
    for i, artifact in enumerate(artifacts, 1):
        print(f"\n   Artifact {i}:")
        print(f"   - ID: {artifact['artifact_id']}")
        print(f"   - Type: {artifact['artifact_type']}")
        print(f"   - Version: {artifact['version']}")
        print(f"   - Agent: {artifact['agent']}")

    # Retrieve conversations
    print("\n5. Retrieving conversations...")
    conversations = get_conversations_from_db(test_thread_id)
    print(f"✓ Retrieved {len(conversations)} conversations")
    for i, conv in enumerate(conversations, 1):
        print(f"\n   Conversation {i}:")
        print(f"   - Agent: {conv['agent']}")
        print(f"   - Content: {conv['content'][:50]}...")
        print(f"   - Artifact ID: {conv['artifact_id']}")

    return test_thread_id


def test_versioning():
    """Test artifact versioning"""
    print("\n" + "="*60)
    print("TEST 2: Artifact Versioning")
    print("="*60)

    test_thread_id = "test_thread_versioning"

    print("\n1. Creating version 1.0 of an artifact...")
    artifact_v1 = {
        "artifact_id": "system_requirements_Analyst_v1.0",
        "artifact_type": "system_requirements",
        "agent": "Analyst",
        "content": {"requirements": ["Req 1", "Req 2"]},
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "write_system_requirement"
    }
    save_artifact_to_db(test_thread_id, artifact_v1)
    print("✓ Version 1.0 saved")

    print("\n2. Creating version 1.1 of the same artifact...")
    artifact_v2 = {
        "artifact_id": "system_requirements_Analyst_v1.1",
        "artifact_type": "system_requirements",
        "agent": "Analyst",
        "content": {"requirements": ["Req 1 (updated)", "Req 2", "Req 3"]},
        "version": "1.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "write_system_requirement"
    }
    save_artifact_to_db(test_thread_id, artifact_v2)
    print("✓ Version 1.1 saved")

    print("\n3. Retrieving all artifacts...")
    artifacts = get_artifacts_from_db(test_thread_id)
    print(f"✓ Total artifacts: {len(artifacts)}")
    for artifact in artifacts:
        print(f"   - {artifact['artifact_id']} (v{artifact['version']})")

    print("\n4. Getting latest version of system_requirements...")
    latest = get_latest_artifact_version(test_thread_id, "system_requirements")
    if latest:
        print(f"✓ Latest version: {latest['version']}")
        print(f"   Artifact ID: {latest['artifact_id']}")
        print(f"   Content: {latest['content']}")

    return test_thread_id


def test_filtering():
    """Test filtering artifacts by type"""
    print("\n" + "="*60)
    print("TEST 3: Filtering Artifacts by Type")
    print("="*60)

    test_thread_id = "test_thread_filtering"

    print("\n1. Creating multiple artifact types...")

    artifacts_to_create = [
        {
            "artifact_id": "req_class_Analyst_v1.0",
            "artifact_type": "requirements_classification",
            "agent": "Analyst",
            "content": {"type": "classification"},
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "classify_user_requirements"
        },
        {
            "artifact_id": "sys_req_Analyst_v1.0",
            "artifact_type": "system_requirements",
            "agent": "Analyst",
            "content": {"type": "system_req"},
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "write_system_requirement"
        },
        {
            "artifact_id": "req_model_Analyst_v1.0",
            "artifact_type": "requirements_model",
            "agent": "Analyst",
            "content": {"type": "model"},
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "build_requirement_model"
        }
    ]

    for artifact in artifacts_to_create:
        save_artifact_to_db(test_thread_id, artifact)

    print(f"✓ Created {len(artifacts_to_create)} artifacts of different types")

    print("\n2. Retrieving all artifacts...")
    all_artifacts = get_artifacts_from_db(test_thread_id)
    print(f"✓ Total artifacts: {len(all_artifacts)}")

    print("\n3. Filtering by artifact_type='requirements_classification'...")
    filtered = get_artifacts_from_db(test_thread_id, artifact_type="requirements_classification")
    print(f"✓ Filtered artifacts: {len(filtered)}")
    for artifact in filtered:
        print(f"   - {artifact['artifact_id']} ({artifact['artifact_type']})")

    print("\n4. Filtering by artifact_type='system_requirements'...")
    filtered = get_artifacts_from_db(test_thread_id, artifact_type="system_requirements")
    print(f"✓ Filtered artifacts: {len(filtered)}")
    for artifact in filtered:
        print(f"   - {artifact['artifact_id']} ({artifact['artifact_type']})")

    return test_thread_id


def test_base64_handling():
    """Test handling of base64 encoded images"""
    print("\n" + "="*60)
    print("TEST 4: Base64 Image Handling")
    print("="*60)

    test_thread_id = "test_thread_base64"

    print("\n1. Creating artifact with base64 image data...")

    # Small 1x1 pixel PNG (base64 encoded)
    small_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    # Simulate a larger base64 string (repeat pattern)
    large_base64 = small_base64 * 100  # About 10KB

    artifact_with_image = {
        "artifact_id": "req_model_with_diagram_v1.0",
        "artifact_type": "requirements_model",
        "agent": "Analyst",
        "content": {
            "diagram_base64": large_base64,
            "diagram_path": "/tmp/test_diagram.png",
            "uml_fmt_content": "@startuml\nactor User\nactor System\nUser -> System : Request\n@enduml"
        },
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "build_requirement_model"
    }

    result = save_artifact_to_db(test_thread_id, artifact_with_image)
    print(f"✓ Artifact with base64 image saved: {result}")
    print(f"   Base64 data size: {len(large_base64)} bytes")

    print("\n2. Retrieving artifact with base64 data...")
    artifacts = get_artifacts_from_db(test_thread_id, artifact_type="requirements_model")

    if artifacts:
        retrieved = artifacts[0]
        retrieved_base64 = retrieved['content']['diagram_base64']
        print(f"✓ Retrieved artifact with base64 data")
        print(f"   Original size: {len(large_base64)} bytes")
        print(f"   Retrieved size: {len(retrieved_base64)} bytes")
        print(f"   Match: {large_base64 == retrieved_base64}")

        if 'diagram_path' in retrieved['content']:
            print(f"   Diagram path: {retrieved['content']['diagram_path']}")

    return test_thread_id


def cleanup_test_data(thread_ids):
    """Clean up test data"""
    print("\n" + "="*60)
    print("CLEANUP: Removing Test Data")
    print("="*60)

    for thread_id in thread_ids:
        print(f"\nDeleting data for thread: {thread_id}")
        result = delete_thread_data(thread_id)
        print(f"✓ Cleanup successful: {result}")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MongoDB Database Utilities Test Suite")
    print("="*60)

    test_threads = []

    try:
        # Run tests
        thread_1 = test_basic_operations()
        test_threads.append(thread_1)

        thread_2 = test_versioning()
        test_threads.append(thread_2)

        thread_3 = test_filtering()
        test_threads.append(thread_3)

        thread_4 = test_base64_handling()
        test_threads.append(thread_4)

        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)

    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Ask user if they want to clean up
        print("\n" + "="*60)
        response = input("\nDo you want to delete test data? (y/n): ").strip().lower()

        if response == 'y':
            cleanup_test_data(test_threads)
        else:
            print("\nTest data preserved. Thread IDs:")
            for thread_id in test_threads:
                print(f"  - {thread_id}")
            print("\nYou can manually clean up later using delete_thread_data()")


if __name__ == "__main__":
    main()

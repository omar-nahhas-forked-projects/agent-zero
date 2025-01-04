import unittest
import os, sys
import json

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from depthio_api import ask_repository_question

class TestDepthioApi(unittest.TestCase):
    
    def setUp(self):
        # Use a real repository for testing
        self.test_repo = "calcom/cal.com"  # Note: github.com prefix will be added automatically
        self.test_question = "What are the main API routes?"

    def test_ask_repository_question(self):
        """Test making an actual API call to Depth.ai"""
        # Make the actual API call
        response = ask_repository_question(self.test_repo, self.test_question)
        
        print("\nAPI Response for valid repo:")
        print(json.dumps(response, indent=2))
        
        # Check if we got an error response
        if 'detail' in response:
            if 'API key does not have access to the repository' in response['detail']:
                self.skipTest("API key doesn't have access to the repository")
            else:
                self.fail(f"API returned an error: {response['detail']}")
        
        if 'error' in response:
            self.fail(f"API returned an error: {response['error']}")
            
        # For successful responses, verify we got content
        self.assertIn('choices', response)
        self.assertTrue(len(response['choices']) > 0)
        self.assertIn('message', response['choices'][0])
        self.assertIn('content', response['choices'][0]['message'])

    def test_invalid_repository(self):
        """Test API behavior with an invalid repository"""
        invalid_repo = "not-a-real-repo/does-not-exist"
        response = ask_repository_question(invalid_repo, self.test_question)
        
        print("\nAPI Response for invalid repo:")
        print(json.dumps(response, indent=2))
        
        # For error responses, verify error details
        self.assertIn('detail', response)
        self.assertIsInstance(response['detail'], str)
        self.assertIn('API key does not have access to the repository', response['detail'])

if __name__ == '__main__':
    unittest.main()

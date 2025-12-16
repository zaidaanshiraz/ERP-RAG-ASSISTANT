"""
User Feedback System for Answer Re-ranking and Quality Improvement.

Implements:
1. User feedback collection (thumbs up/down + comments)
2. Feedback-based re-ranking of retrieved documents
3. Analytics dashboard for system improvement
4. Export feedback data for model fine-tuning
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class FeedbackManager:
    """Manage user feedback and re-ranking based on feedback history."""
    
    def __init__(self, feedback_file: str = "data/feedback/user_feedback.json"):
        """
        Initialize feedback manager.
        
        Args:
            feedback_file: Path to JSON file storing feedback
        """
        self.feedback_file = Path(feedback_file)
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing feedback
        self.feedback_data = self._load_feedback()
        
        # Track document performance
        self.document_scores = self._calculate_document_scores()
    
    def _load_feedback(self) -> List[Dict]:
        """Load feedback from JSON file."""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading feedback: {e}")
                return []
        return []
    
    def _save_feedback(self):
        """Save feedback to JSON file."""
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(self.feedback_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
    
    def add_feedback(
        self,
        query: str,
        answer: str,
        sources: List[Dict],
        rating: str,
        comment: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Add user feedback for a query-answer pair.
        
        Args:
            query: User question
            answer: Generated answer
            sources: Retrieved source documents
            rating: 'positive' or 'negative'
            comment: Optional user comment
            user_id: Optional user identifier
        
        Returns:
            Feedback record
        """
        feedback_entry = {
            "feedback_id": len(self.feedback_data) + 1,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "answer": answer,
            "sources": sources,
            "rating": rating,
            "comment": comment,
            "user_id": user_id,
            "session_id": f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        
        self.feedback_data.append(feedback_entry)
        self._save_feedback()
        
        # Update document scores
        self._update_document_scores(sources, rating)
        
        logger.info(f"Feedback recorded: {rating} for query '{query[:50]}...'")
        return feedback_entry
    
    def _calculate_document_scores(self) -> Dict[str, Dict]:
        """Calculate performance scores for each document based on feedback."""
        scores = {}
        
        for feedback in self.feedback_data:
            for source in feedback.get("sources", []):
                doc_name = source.get("document_name", "unknown")
                
                if doc_name not in scores:
                    scores[doc_name] = {
                        "positive": 0,
                        "negative": 0,
                        "total": 0,
                        "score": 0.5  # Neutral starting score
                    }
                
                scores[doc_name]["total"] += 1
                if feedback["rating"] == "positive":
                    scores[doc_name]["positive"] += 1
                else:
                    scores[doc_name]["negative"] += 1
                
                # Calculate score (0 to 1)
                total = scores[doc_name]["total"]
                positive = scores[doc_name]["positive"]
                scores[doc_name]["score"] = positive / total if total > 0 else 0.5
        
        return scores
    
    def _update_document_scores(self, sources: List[Dict], rating: str):
        """Update document scores based on new feedback."""
        for source in sources:
            doc_name = source.get("document_name", "unknown")
            
            if doc_name not in self.document_scores:
                self.document_scores[doc_name] = {
                    "positive": 0,
                    "negative": 0,
                    "total": 0,
                    "score": 0.5
                }
            
            self.document_scores[doc_name]["total"] += 1
            if rating == "positive":
                self.document_scores[doc_name]["positive"] += 1
            else:
                self.document_scores[doc_name]["negative"] += 1
            
            # Recalculate score
            total = self.document_scores[doc_name]["total"]
            positive = self.document_scores[doc_name]["positive"]
            self.document_scores[doc_name]["score"] = positive / total if total > 0 else 0.5
    
    def rerank_sources(self, sources: List[Dict]) -> List[Dict]:
        """
        Re-rank sources based on historical feedback.
        
        Args:
            sources: List of retrieved sources with relevance scores
        
        Returns:
            Re-ranked sources
        """
        # Apply feedback-based boost
        for source in sources:
            doc_name = source.get("document_name", "unknown")
            
            # Get document quality score (0 to 1)
            doc_score = self.document_scores.get(doc_name, {}).get("score", 0.5)
            
            # Boost original relevance score by document quality
            # Original score weight: 70%, feedback score weight: 30%
            original_score = source.get("relevance_score", 0.5)
            boosted_score = (original_score * 0.7) + (doc_score * 0.3)
            
            source["relevance_score"] = boosted_score
            source["feedback_boost"] = doc_score
        
        # Sort by boosted score
        return sorted(sources, key=lambda x: x["relevance_score"], reverse=True)
    
    def get_analytics(self) -> Dict:
        """
        Get feedback analytics dashboard data.
        
        Returns:
            Analytics summary
        """
        total_feedback = len(self.feedback_data)
        if total_feedback == 0:
            return {
                "total_feedback": 0,
                "satisfaction_rate": 0,
                "positive_count": 0,
                "negative_count": 0,
                "top_documents": [],
                "problematic_documents": []
            }
        
        positive_count = sum(1 for f in self.feedback_data if f["rating"] == "positive")
        negative_count = total_feedback - positive_count
        satisfaction_rate = (positive_count / total_feedback) * 100
        
        # Top performing documents
        top_docs = sorted(
            self.document_scores.items(),
            key=lambda x: (x[1]["score"], x[1]["total"]),
            reverse=True
        )[:5]
        
        # Problematic documents
        problematic_docs = sorted(
            [(doc, stats) for doc, stats in self.document_scores.items() if stats["total"] >= 3],
            key=lambda x: x[1]["score"]
        )[:5]
        
        return {
            "total_feedback": total_feedback,
            "satisfaction_rate": satisfaction_rate,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "top_documents": [
                {
                    "document": doc,
                    "score": f"{stats['score']*100:.1f}%",
                    "positive": stats["positive"],
                    "negative": stats["negative"],
                    "total": stats["total"]
                }
                for doc, stats in top_docs
            ],
            "problematic_documents": [
                {
                    "document": doc,
                    "score": f"{stats['score']*100:.1f}%",
                    "positive": stats["positive"],
                    "negative": stats["negative"],
                    "total": stats["total"]
                }
                for doc, stats in problematic_docs
            ],
            "recent_comments": [
                {
                    "query": f["query"][:50] + "...",
                    "rating": f["rating"],
                    "comment": f.get("comment", ""),
                    "timestamp": f["timestamp"]
                }
                for f in self.feedback_data[-10:][::-1]
                if f.get("comment")
            ]
        }
    
    def export_for_finetuning(self, output_file: str = "data/feedback/finetuning_data.jsonl"):
        """
        Export positive feedback as training data for fine-tuning.
        
        Format: JSONL with query-answer pairs
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        training_data = []
        for feedback in self.feedback_data:
            if feedback["rating"] == "positive":
                training_data.append({
                    "query": feedback["query"],
                    "answer": feedback["answer"],
                    "sources": feedback["sources"],
                    "context": " ".join([s.get("excerpt", "") for s in feedback["sources"]])
                })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in training_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        logger.info(f"Exported {len(training_data)} training examples to {output_file}")
        return len(training_data)


# Example usage
if __name__ == "__main__":
    # Initialize feedback manager
    manager = FeedbackManager()
    
    # Add sample feedback
    manager.add_feedback(
        query="What is accounts payable?",
        answer="Accounts payable is...",
        sources=[{"document_name": "sample_erp_guide.pdf", "excerpt": "..."}],
        rating="positive",
        comment="Very helpful!"
    )
    
    # Get analytics
    analytics = manager.get_analytics()
    print(f"Satisfaction Rate: {analytics['satisfaction_rate']:.1f}%")
    
    # Export training data
    manager.export_for_finetuning()

"""
Base Parser Interface
"""
from abc import ABC, abstractmethod

class InvoiceParser(ABC):
    """Abstract base class for invoice parsers"""
    
    @abstractmethod
    def can_handle(self, ocr_text: str) -> bool:
        """Check if this parser can handle the given invoice"""
        pass
    
    @abstractmethod
    def extract_vehicles(self, pages_data: list, full_text: str) -> list:
        """Extract vehicle information from invoice"""
        pass
    
    @abstractmethod
    def extract_invoice_number(self, text: str) -> str:
        """Extract invoice number"""
        pass
    
    @abstractmethod
    def extract_color(self, pages_data: list) -> str:
        """Extract vehicle color"""
        pass

from rest_framework.parsers import MultiPartParser, DataAndFiles

class NestedMultipartParser(MultiPartParser):
    """
    Parser for handling nested multipart/form-data.
    """
    
    def parse(self, stream, media_type=None, parser_context=None):
        result = super().parse(stream, media_type, parser_context)
        
        data = {}
        files = {}
        
        # Process regular data fields
        for key, value in result.data.items():
            if '[' in key and ']' in key:
                # Nested field: documents[0][document_type]
                self._add_nested_field(data, key, value)
            else:
                # Regular field
                data[key] = value
        
        # Process file fields
        for key, value in result.files.items():
            if '[' in key and ']' in key:
                # Nested file: documents[0][uploaded_file]
                self._add_nested_field(data, key, value, is_file=True)
            else:
                # Regular file
                files[key] = value
        
        # Return DataAndFiles object
        return DataAndFiles(data, files)
    
    def _add_nested_field(self, data_dict, key, value, is_file=False):
        """
        Convert nested field notation to nested dict/list structure.
        
        Supports both object and array notation:
            'user[email]' -> data_dict['user']['email']  (object)
            'documents[0][document_type]' -> data_dict['documents'][0]['document_type']  (array)
        """
        # Parse field name: user[email] or documents[0][document_type]
        parts = key.replace(']', '').split('[')
        
        if len(parts) == 2:
            # Object notation: user[email]
            object_name = parts[0]  # 'user'
            field_name = parts[1]   # 'email'
            
            # Initialize dict if not exists
            if object_name not in data_dict:
                data_dict[object_name] = {}
            
            # Set the value
            data_dict[object_name][field_name] = value
            
        elif len(parts) == 3:
            # Array notation: documents[0][document_type]
            list_name = parts[0]  # 'documents'
            index = int(parts[1])  # 0
            field_name = parts[2]  # 'document_type'
            
            # Initialize list if not exists
            if list_name not in data_dict:
                data_dict[list_name] = []
            
            # Extend list if needed
            while len(data_dict[list_name]) <= index:
                data_dict[list_name].append({})
            
            # Set the value
            data_dict[list_name][index][field_name] = value
        else:
            # Not a nested field, treat as regular
            data_dict[key] = value

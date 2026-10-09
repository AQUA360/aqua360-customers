import logging
import re
import json
from datetime import datetime
from urllib.parse import parse_qs

logger = logging.getLogger("post_requests")


class PostRequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.sensitive_fields = {'password', 'fill with your sensitive fields'}  
    
    def _mask_sensitive_data(self, data):
        if isinstance(data, dict):
            return {
                k: '***REDACTED***' if k.lower() in self.sensitive_fields else self._mask_sensitive_data(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        return data
    
    def _parse_multipart(self, request):
        data = {}
        
        for key, value in request.POST.items():
            data[key] = value
        
        files_info = {}
        for key, file_obj in request.FILES.items():
            files_info[key] = {
                'filename': file_obj.name,
                'content_type': file_obj.content_type,
                'size': f"{file_obj.size} bytes" if file_obj.size else "unknown",
            }
        
        if files_info:
            data['__files__'] = files_info
        
        return data
    
    def _parse_body(self, body, content_type, request=None):
        try:
            if 'application/json' in content_type:
                parsed = json.loads(body)
                return json.dumps(self._mask_sensitive_data(parsed), indent=2)
            
            elif 'application/x-www-form-urlencoded' in content_type:
                parsed = parse_qs(body)

                parsed = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
                masked = self._mask_sensitive_data(parsed)
                return json.dumps(masked, indent=2)
            
            elif 'multipart/form-data' in content_type:
                if request:
                    multipart_data = self._parse_multipart(request)
                    masked = self._mask_sensitive_data(multipart_data)
                    return json.dumps(masked, indent=2)
                return "<multipart/form-data - unable to parse>"
            
            else:
                # Try to parse as JSON anyway
                try:
                    parsed = json.loads(body)
                    return json.dumps(self._mask_sensitive_data(parsed), indent=2)
                except:
                    return body if len(body) < 500 else f"{body[:500]}... (truncated)"
        
        except Exception as e:
            return f"<parse error: {str(e)}>"
    
    def _parse_response(self, response):
        try:
            content_type = response.get('Content-Type', '')
            
            # Check if response has content
            if hasattr(response, 'content'):
                content = response.content.decode('utf-8')
                
                # Try to parse as JSON
                if 'application/json' in content_type or content.strip().startswith('{') or content.strip().startswith('['):
                    try:
                        parsed = json.loads(content)
                        return json.dumps(self._mask_sensitive_data(parsed), indent=2)
                    except:
                        pass
                
                # Return truncated if too long
                if len(content) > 500:
                    return f"{content[:500]}... (truncated)"
                
                return content
            
            return "<no content>"
        
        except Exception as e:
            return f"<parse error: {str(e)}>"
    
    def _get_status_emoji(self, status_code):
        if 200 <= status_code < 300:
            return "✅"
        elif 300 <= status_code < 400:
            return "↪️"
        elif 400 <= status_code < 500:
            return "⚠️"
        elif 500 <= status_code < 600:
            return "❌"
        return "❓"
    
    def __call__(self, request):
        if request.method == "POST" and request.path.startswith("/ov/"):
            user = getattr(request, "user", None)
            user_repr = user.username if user and user.is_authenticated else "Anonymous"
            
            
            content_type = request.content_type or 'unknown'
            
            
            try:
                body_raw = request.body.decode("utf-8")
                body_formatted = self._parse_body(body_raw, content_type, request)
            except Exception:
                body_formatted = "<unreadable>"
            
            # Record start time
            start_time = datetime.now()
        
        # Get response
        response = self.get_response(request)
        
        if request.method == "POST" and request.path.startswith("/ov/"):
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000 
            
            response_body = self._parse_response(response)
            status_emoji = self._get_status_emoji(response.status_code)
            
            log_message = (
                f"\n{'='*80}\n"
                f"POST REQUEST {status_emoji}\n"
                f"{'-'*80}\n"
                f"Timestamp:     {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"User:          {user_repr}\n"
                f"Path:          {request.path}\n"
                f"Content-Type:  {content_type}\n"
                f"IP Address:    {self._get_client_ip(request)}\n"
                f"{'-'*80}\n"
                f"Request Data:\n"
                f"{body_formatted}\n"
                f"{'-'*80}\n"
                f"Response:\n"
                f"Status Code:   {response.status_code}\n"
                f"Duration:      {duration:.2f}ms\n"
                f"Response Data:\n"
                f"{response_body}\n"
                f"{'='*80}"
            )
            
            logger.info(log_message)
        
        return response
    
    def _get_client_ip(self, request):
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
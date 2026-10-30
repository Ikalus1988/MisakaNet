def scan_string(self):
    self.match('"')
    string_value = ''
    while self.peek() != '"' and not self.is_at_end():
        string_value += self.advance()
    self.match('"')
    return Token(TokenType.STRING, string_value, string_value, self.previous.line)
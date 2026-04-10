# Ethics and Compliance Guide

## Overview

This document outlines the ethical principles, legal considerations, and compliance requirements for using MCMonitor. Understanding and following these guidelines is essential for responsible server monitoring.

## Core Ethical Principles

### 1. Consent and Authorization

**Always obtain explicit permission** before monitoring servers you don't own:

- ✅ **Your own servers**: Full monitoring rights
- ✅ **Servers with written permission**: Document the authorization
- ✅ **Public opt-in APIs**: Servers listed have agreed to discovery
- ❌ **Random servers without consent**: Prohibited
- ❌ **Servers that explicitly forbid monitoring**: Respect their wishes

### 2. Minimal Data Collection

Collect only what's necessary:

- ✅ **Status information**: Online/offline, player counts, version
- ✅ **MOTD**: Publicly displayed message
- ⚠️ **Player names**: Only if voluntarily provided by server
- ❌ **IP addresses of players**: Never collect
- ❌ **Chat logs**: Never attempt to access
- ❌ **Authentication data**: Never attempt to capture

### 3. Resource Respect

Don't impact server performance:

- ✅ **Reasonable polling intervals**: ≥60 seconds recommended
- ✅ **Rate limiting**: Stay within configured limits
- ✅ **Connection timeouts**: Don't hold connections open
- ❌ **Rapid repeated queries**: Can be considered DoS
- ❌ **Concurrent connections per server**: Limit to 1-5 max

### 4. Transparency

Be open about your monitoring:

- ✅ **Identify your tool**: Use descriptive User-Agent strings
- ✅ **Document purpose**: Keep records of why you monitor each server
- ✅ **Respond to inquiries**: Be available to answer questions
- ❌ **Hidden monitoring**: Don't try to conceal your activity

## Legal Considerations

### Computer Fraud and Abuse Act (CFAA) - USA

The CFAA prohibits unauthorized access to computer systems. Key points:

- Accessing publicly available information is generally permitted
- Bypassing authentication or access controls is prohibited
- Excessive polling could be construed as unauthorized access
- Violating Terms of Service may constitute unauthorized access

**Compliance**: Only access publicly exposed server status via standard protocols.

### General Data Protection Regulation (GDPR) - EU

Player names may constitute personal data under GDPR:

- **Lawful basis**: Legitimate interest or consent
- **Data minimization**: Collect only necessary data
- **Purpose limitation**: Use only for stated purposes
- **Storage limitation**: Don't retain data longer than needed
- **Security**: Protect collected data appropriately

**Compliance**: Use `--no-player-names` flag if uncertain about lawful basis.

### Minecraft EULA

The [Minecraft End User License Agreement](https://account.mojang.com/documents/minecraft_eula) governs use of Minecraft:

- **Section 2**: You may not distribute modified clients/servers
- **Section 3**: You may not access Mojang services in unauthorized ways
- **Section 5**: Commercial use requires separate agreement

**Our tool complies by**:
- Using official server ping protocol only
- Not modifying game files or behavior
- Not accessing authentication services
- Being free and open-source

### Terms of Service

Individual servers may have their own ToS:

- Check server websites for monitoring policies
- Some servers explicitly allow monitoring
- Some servers explicitly prohibit it
- When in doubt, ask the server owner

## What This Tool Does NOT Do

It's important to understand the limitations:

### ❌ No IP Scanning
This tool cannot and will not scan IP ranges to discover servers. It only monitors explicitly provided addresses.

### ❌ No Port Sweeping
The tool uses standard Minecraft port (25565) or user-specified ports only. It does not probe multiple ports.

### ❌ No Authentication Bypass
The tool cannot and will not attempt to bypass authentication, login to servers, or access protected resources.

### ❌ No Credential Harvesting
No mechanism exists to capture usernames, passwords, tokens, or any authentication credentials.

### ❌ No Protocol Exploitation
The tool uses only the official Server List Ping protocol as documented by Mojang.

### ❌ No Hidden Data Collection
All data collection is logged and visible in the output files. Nothing is collected secretly.

## Best Practices Checklist

Before deploying MCMonitor:

- [ ] I own the servers I'm monitoring OR have written permission
- [ ] I've reviewed each server's Terms of Service
- [ ] I've set appropriate polling intervals (≥60s unless justified)
- [ ] I've configured rate limiting appropriately
- [ ] I understand what data is being collected
- [ ] I've secured log files with appropriate permissions
- [ ] I have a legitimate purpose for monitoring
- [ ] I can explain my monitoring if asked
- [ ] I've considered GDPR implications for any player data
- [ ] I'm prepared to stop if a server owner objects

## Obtaining Server Owner Permission

Template for requesting permission:

```
Subject: Request to Monitor [Server Name] Status

Dear [Server Owner/Admin],

I am writing to request permission to monitor the public status of your 
Minecraft server [server address].

Purpose: [Explain why - e.g., "uptime monitoring for a community dashboard"]

Data collected:
- Online/offline status
- Player count (aggregate number only)
- Server version and MOTD
- Response latency

Monitoring frequency: Every [X] minutes

Data handling:
- Logs stored securely with restricted access
- Retained for [X] days/months
- Not shared with third parties
- Player names excluded [or included if server provides them]

You can revoke this permission at any time by contacting me at [contact info].

Please let me know if you have any questions or concerns.

Best regards,
[Your name]
[Contact information]
```

## Incident Response

If you receive a complaint or takedown request:

1. **Stop immediately**: Cease monitoring the server in question
2. **Document**: Record the complaint and your response
3. **Review**: Verify you had proper authorization
4. **Respond**: Acknowledge and address the concern
5. **Learn**: Update practices to prevent future issues

## API Usage Ethics

When using public APIs (mcstatus.io, minecraft-mp.com):

- **Check rate limits**: Stay well within published limits
- **Use caching**: Don't re-query unnecessarily
- **Identify yourself**: Use proper User-Agent strings
- **Consider API keys**: Support API providers when possible
- **Read ToS**: Each API has its own terms

## Privacy Mode

For maximum privacy compliance, use:

```bash
mcmonitor run --servers servers.json --no-player-names
```

This ensures no player identifiers are ever recorded, even if servers provide them.

## Security Recommendations

Protect your monitoring infrastructure:

1. **File permissions**: Restrict access to logs and configs
   ```bash
   chmod 700 /path/to/mcmonitor/logs
   chmod 600 /path/to/mcmonitor/logs/*
   ```

2. **Network security**: Use firewall rules to limit outbound connections

3. **Log rotation**: Prevent disk exhaustion and limit data retention
   ```bash
   # Configure in settings or use logrotate
   ```

4. **Access control**: Run as non-root user with minimal privileges

5. **Audit trails**: Keep logs of who accessed monitoring data

## Jurisdiction-Specific Notes

### United States
- CFAA compliance is critical
- DMCA may apply to certain data uses
- State laws may impose additional requirements

### European Union
- GDPR applies to any EU player data
- ePrivacy Directive may require consent
- National implementations vary

### Other Jurisdictions
- Consult local legal counsel
- Some countries have specific data localization requirements
- Export controls may apply to monitoring tools

## Resources

- [Minecraft EULA](https://account.mojang.com/documents/minecraft_eula)
- [GDPR Text](https://gdpr.eu/)
- [CFAA Summary](https://www.eff.org/issues/coders/cookbook)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)

## Contact

For ethics-related questions or concerns:
- Review this documentation thoroughly
- Consult with legal counsel for specific situations
- Reach out to the project maintainers for clarification

---

**Remember**: Just because something is technically possible doesn't mean it's ethical or legal. When in doubt, err on the side of caution and respect server owners' rights.

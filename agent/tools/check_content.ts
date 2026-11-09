import { defineTool } from 'eve/tools';
import { z } from 'zod';

export default defineTool({
  description: 'Check a draft for essential publishing details. This checks supplied fields only; it does not publish or verify claims.',
  inputSchema: z.object({
    platform: z.enum(['instagram','facebook','pinterest','youtube']),
    format: z.enum(['post','reel','story','short','pin']),
    caption: z.string().min(1).max(5000),
    mediaProvided: z.boolean(),
    bookFactsVerified: z.boolean(),
    amazonLinkVerified: z.boolean(),
  }),
  async execute(input) {
    const issues: string[] = [];
    if (!input.mediaProvided) issues.push('No owned media provided.');
    if (!input.bookFactsVerified) issues.push('Book facts need verification.');
    if (!input.amazonLinkVerified) issues.push('Amazon destination needs verification.');
    return {readyForReview: issues.length === 0, issues, postingConnected: false};
  },
});

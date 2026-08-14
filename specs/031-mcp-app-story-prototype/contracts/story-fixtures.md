# Contract: Story Fixtures

Each scene fixture contains:

```ts
interface StoryScene {
  id: StorySceneId;
  order: number;
  icon: LucideIconName;
  availability: "ready" | "permission" | "recovery";
  title: LocalizedText;
  userMessage: LocalizedText;
  assistantLead: LocalizedText;
  tools: StoryToolActivity[];
  conclusion: LocalizedText;
  schema: string;
  renderer: StoryRenderer;
  presentation: "conversation" | "confirmation" | "app" | "status";
}
```

Invariants:

- IDs are unique and stable URL values.
- Orders are contiguous from 1 through 7.
- Tool names are real QMT-MCP names or explicitly marked proposed names.
- Fixture arguments contain no credentials, tokens, host addresses, or real
  account identifiers.
- `permission` scenes cannot expose an execution action.
- Every locale has complete visible copy; no mixed-language shell fallback.
- Only `presentation: "app"` scenes render a framed MCP App. Other presentations
  stay within the host transcript and do not imply an App resource.

using System.Text.Json.Nodes;
namespace TD.Poc.Core;

// Intent memory only. Generated answers and remembered facts are never evidence.
public sealed class ConversationState
{
    private readonly List<JsonNode> turns=[];
    public void Clear()=>turns.Clear();
    public JsonObject Snapshot()=>new(){{"active_task",turns.LastOrDefault()?["interpreted_task"]?.DeepClone()},{"pending_question_or_gap",turns.LastOrDefault()?["pending_question_or_gap"]?.DeepClone()},{"purpose","Conversation intent only; retrieve original evidence for product facts."},{"turns",new JsonArray(turns.Select(x=>x.DeepClone()).ToArray())}};
    public void Record(string question,JsonNode? intent,string status,string pending)
    {
        if(intent?["conversation_relation"]?.ToString()=="NEW")turns.Clear();
        turns.Add(new JsonObject{{"user_message",question},{"interpreted_task",intent?.DeepClone()},{"status",status},{"pending_question_or_gap",pending[..Math.Min(pending.Length,2000)]}});
        if(turns.Count>4)turns.RemoveAt(0);
    }
}

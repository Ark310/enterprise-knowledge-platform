using System.Text.Json.Nodes;
namespace TD.Poc.Core;

// Intent memory only. Generated answers and remembered facts are never evidence.
public sealed class ConversationState
{
    private readonly List<JsonNode> turns=[];
    public void Clear()=>turns.Clear();
    public void Restore(JsonNode? snapshot){turns.Clear();if(snapshot?["turns"] is JsonArray items)foreach(var t in items.TakeLast(4))if(t is not null)turns.Add(t.DeepClone());}
    public JsonObject Snapshot()=>new(){{"active_task",turns.LastOrDefault()?["interpreted_task"]?.DeepClone()},{"pending_question_or_gap",turns.LastOrDefault()?["pending_question_or_gap"]?.DeepClone()},{"purpose","Conversation intent only; retrieve original evidence for product facts."},{"turns",new JsonArray(turns.Select(x=>x.DeepClone()).ToArray())}};
    public void Record(string question,JsonNode? intent,string status,string pending,string? replyReference=null)
    {
        if(intent?["conversation_relation"]?.ToString()=="NEW")turns.Clear();
        turns.Add(new JsonObject{{"user_message",question},{"interpreted_task",intent?.DeepClone()},{"status",status},{"assistant_reply_reference",replyReference is null?null:replyReference[..Math.Min(replyReference.Length,6000)]},{"pending_question_or_gap",pending[..Math.Min(pending.Length,2000)]}});
        if(turns.Count>4)turns.RemoveAt(0);
    }
}

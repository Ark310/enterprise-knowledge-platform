using System.Text.Json.Nodes;
namespace TD.Poc.Core;

// Model content errors get bounded repair. Process, cancellation and database errors propagate.
public static class BatchRecovery
{
    public static async Task Run(Func<int,JsonNode?,Task> generate,Func<Task<JsonNode>> validate)
    {
        JsonNode? feedback=null;
        for(var attempt=1;attempt<=3;attempt++)
        {
            await generate(attempt,feedback);
            feedback=await validate();
            if(feedback["valid"]?.GetValue<bool>()==true)return;
        }
        throw new InvalidOperationException("B batch failed validation after initial attempt and two corrections: "+feedback);
    }
}

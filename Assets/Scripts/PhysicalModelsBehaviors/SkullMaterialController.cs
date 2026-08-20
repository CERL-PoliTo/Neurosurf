using UnityEngine;

public class SkullMaterialController : MonoBehaviour
{
    private Material material;
    private string propertyAlpha;
    
    private void Start()
    {
        material = GetComponent<MeshRenderer>().material;
        propertyAlpha = GameManager.instance.GetPropertyAlpha(ModelLayerSelector.Skull);
        material.renderQueue = GameManager.instance.GetRenderQueue(ModelLayerSelector.Skull);
    }

    public void SetAlpha(float value)
    {
        material.SetFloat(propertyAlpha, value);
    }
}

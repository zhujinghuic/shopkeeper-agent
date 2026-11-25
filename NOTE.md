# 关联教程连接
https://github.com/didilili/ai-agents-from-zero/tree/main/%E5%AE%9E%E6%88%98%E9%A1%B9%E7%9B%AE-%E7%94%B5%E5%95%86%E9%97%AE%E6%95%B0


# 理解
### 为啥选用Qrdant做向量数据库？
1. payload 跟着向量一起存
每个点带一份完整 ColumnInfo，搜出来就能直接用，不用再回 MySQL 查一遍。这是项目最依赖的特性。

2. 支持 payload 过滤
Qdrant 可以在向量检索时加条件，比如“只在 role = measure 的字段里搜”。项目现在没用，但以后要缩小范围很方便。

3. 适合“一个对象拆多个点”
项目的字段拆成 name/description/alias 多个点，Qdrant 对这种多向量点、多 collection 的支持很自然。

if(typeof(Array.prototype.reduce) === "undefined" || Array.prototype.reduce === null)
{
    Array.prototype.reduce = function(fn)
    {
        return _.reduce(this, fn);
    }
}